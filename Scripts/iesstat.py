import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import glob
from scipy.stats import ttest_rel
from statsmodels.stats.anova import AnovaRM

# Constants
RESPONSE_THRESHOLD = 1000  # in ms
SHOOT_WINDOW = 30
PREP_WINDOW_START = -120
PREP_WINDOW_END = 0

def group_noshot_events(df):
    noshot_df = df[df['Experiment'].str.startswith("OptimalMoment", na=False)].copy()
    groups = []
    current_group = []
    prev_time = None
    for _, row in noshot_df.iterrows():
        if prev_time is not None and row['Timestamp'] - prev_time > 100:
            groups.append(current_group)
            current_group = []
        current_group.append(row['Timestamp'])
        prev_time = row['Timestamp']
    if current_group:
        groups.append(current_group)
    return [np.mean(group) for group in groups]

def load_and_filter_data(file_path):
    df = pd.read_csv(file_path, header=0, usecols=[0, 1, 2, 3])
    df = df[df['Experiment'].notna()]
    df = df[~df['Experiment'].str.contains("Staircase Procedure", na=False)]
    df['Timestamp'] = pd.to_numeric(df['Timestamp'])
    df['Response'] = df['Response'].astype(str).str.strip()
    return df

def is_in_prep_window(vibration_time, shoot_times):
    return np.any((shoot_times + PREP_WINDOW_START <= vibration_time) &
                  (vibration_time <= shoot_times + PREP_WINDOW_END))

def process_subject(file_path):
    df = load_and_filter_data(file_path)
    vibrations = df[df['Experiment'].str.startswith("VibrationSent", na=False)].copy()
    player_shoots = df[df['Experiment'].str.startswith("PlayerShoot", na=False)].copy()
    foot_df = df[df['Experiment'].str.startswith("FootPedalPress", na=False)].copy()

    shoot_times = player_shoots['Timestamp'].values
    foot_times = foot_df['Timestamp'].values

    optimal_moments = group_noshot_events(df)
    valid_optimal_moments = [
        om_time for om_time in optimal_moments
        if not np.any((player_shoots['Timestamp'] >= om_time - SHOOT_WINDOW) &
                      (player_shoots['Timestamp'] <= om_time + SHOOT_WINDOW))
    ]
    valid_optimal_moments = np.array(valid_optimal_moments)

    vibrations['CorrectResponse'] = 0
    vibrations['RT'] = np.nan

    for idx, row in vibrations.iterrows():
        vib_time = row['Timestamp']
        valid_press = foot_df[(foot_df['Timestamp'] >= vib_time) &
                              (foot_df['Timestamp'] <= vib_time + RESPONSE_THRESHOLD)]
        if not valid_press.empty:
            rt = valid_press.iloc[0]['Timestamp'] - vib_time
            vibrations.at[idx, 'CorrectResponse'] = 1
            vibrations.at[idx, 'RT'] = rt

    vibrations['InOptimalMoment'] = vibrations['Timestamp'].apply(
        lambda t: np.any(np.abs(valid_optimal_moments - t) < SHOOT_WINDOW))
    vibrations['InPrepWindow'] = vibrations['Timestamp'].apply(
        lambda t: is_in_prep_window(t, shoot_times))

    vibrations['Category'] = "Outside Window"
    vibrations.loc[vibrations['InPrepWindow'], 'Category'] = "Prep Window"
    vibrations.loc[vibrations['InOptimalMoment'], 'Category'] = "Optimal Moment"

    results = {}
    for category in ["Optimal Moment", "Prep Window", "Outside Window"]:
        subset = vibrations[vibrations['Category'] == category]
        total = len(subset)
        correct_subset = subset[subset['CorrectResponse'] == 1]
        correct = len(correct_subset)
        accuracy = correct / total if total > 0 else np.nan
        mean_rt = correct_subset['RT'].mean() if correct > 0 else np.nan
        ies = mean_rt / accuracy if accuracy > 0 else np.nan
        results[category] = {
            'accuracy': accuracy * 100 if accuracy is not np.nan else np.nan,
            'mean_rt': mean_rt,
            'ies': ies
        }
    return results

def compute_cohens_d(x, y):
    x = np.array(x)
    y = np.array(y)
    diff = x - y
    return np.mean(diff) / np.std(diff, ddof=1)

def main():
    all_files = glob.glob("experiment_responses_*.csv")
    categories = ["Optimal Moment", "Prep Window", "Outside Window"]

    acc_data = {cat: [] for cat in categories}
    ies_data = {cat: [] for cat in categories}
    valid_subject_indices = []

    for idx, file in enumerate(all_files):
        res = process_subject(file)
        if all(not np.isnan(res[cat]['ies']) for cat in categories):
            valid_subject_indices.append(idx)
            for cat in categories:
                acc_data[cat].append(res[cat]['accuracy'])
                ies_data[cat].append(res[cat]['ies'])
        else:
            print(f"⚠️ Skipped {file}: NaN IES found in one or more conditions")

    # Plot IES
    mean_ies = [np.mean(ies_data[cat]) for cat in categories]
    sem_ies = [np.std(ies_data[cat], ddof=1) / np.sqrt(len(ies_data[cat])) for cat in categories]
    n_per_cat = [len(ies_data[cat]) for cat in categories]

    plt.figure(figsize=(8, 6))
    bars = plt.bar(categories, mean_ies, yerr=sem_ies, capsize=5,
                   color=["skyblue", "lightgreen", "salmon"])
    plt.ylabel("Inverse Efficiency Score (ms)")
    plt.title(f"Group-Averaged IES with SEM (n={min(n_per_cat)})")

    for i, val in enumerate(mean_ies):
        plt.text(i, val + 20, f"{val:.1f}", ha="center", va="bottom", fontsize=10)

    plt.tight_layout()
    plt.show()

    # Repeated-Measures ANOVA
    print("\n--- Repeated-Measures ANOVA on IES ---")
    long_data = []
    for i, idx in enumerate(valid_subject_indices):
        for cat in categories:
            long_data.append({
                "Subject": i,
                "Condition": cat,
                "IES": ies_data[cat][i]
            })
    df_long = pd.DataFrame(long_data)
    anova = AnovaRM(df_long, depvar='IES', subject='Subject', within=['Condition']).fit()
    print(anova)

    # Paired t-tests
    print("\n--- Paired t-tests on IES ---")
    pairs = [("Optimal Moment", "Prep Window"),
             ("Optimal Moment", "Outside Window"),
             ("Prep Window", "Outside Window")]
    for cat1, cat2 in pairs:
        x = np.array(ies_data[cat1])
        y = np.array(ies_data[cat2])
        t_stat, p_val = ttest_rel(x, y)
        d = compute_cohens_d(x, y)
        sig = "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else ""
        print(f"{cat1} vs {cat2}: t = {t_stat:.3f}, p = {p_val:.5f}, d = {d:.2f} {sig}")

if __name__ == "__main__":
    main()
