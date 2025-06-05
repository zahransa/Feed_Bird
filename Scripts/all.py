import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import glob

# Constants
RESPONSE_THRESHOLD = 1000  # 1 second (ms)
SHOOT_WINDOW = 30  # ±30 ms to check for PlayerShoot
PREP_WINDOW_START = -120  # ms before PlayerShoot
PREP_WINDOW_END = -50       # ms up to PlayerShoot

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
    return np.any((shoot_times + PREP_WINDOW_START <= vibration_time) & (vibration_time <= shoot_times + PREP_WINDOW_END))

def has_foot_response(vibration_time, foot_times):
    return 1 if np.any((foot_times >= vibration_time) & (foot_times <= vibration_time + RESPONSE_THRESHOLD)) else 0

def compute_sem(correct_responses, total_responses):
    if total_responses > 0:
        p = correct_responses / total_responses
        return np.sqrt(p * (1 - p) / total_responses) * 100
    return np.nan

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

    vibrations['CorrectResponse'] = vibrations['Timestamp'].apply(lambda t: has_foot_response(t, foot_times))
    vibrations['InOptimalMoment'] = vibrations['Timestamp'].apply(lambda t: np.any(np.abs(valid_optimal_moments - t) < SHOOT_WINDOW))
    vibrations['InPrepWindow'] = vibrations['Timestamp'].apply(lambda t: is_in_prep_window(t, shoot_times))

    vibrations['Category'] = "Outside Window"
    vibrations.loc[vibrations['InPrepWindow'], 'Category'] = "Prep Window"
    vibrations.loc[vibrations['InOptimalMoment'], 'Category'] = "Optimal Moment"

    rates = {}
    for category in ["Optimal Moment", "Prep Window", "Outside Window"]:
        subset = vibrations[vibrations['Category'] == category]
        total = len(subset)
        correct = subset['CorrectResponse'].sum()
        rate = (correct / total * 100) if total > 0 else np.nan
        sem = compute_sem(correct, total)
        rates[category] = (rate, sem, total)
    return rates

def main():
    all_files = glob.glob("experiment_responses_*.csv")
    category_names = ["Optimal Moment", "Prep Window", "Outside Window"]
    all_rates = {cat: [] for cat in category_names}
    all_sems = {cat: [] for cat in category_names}

    for file in all_files:
        subject_rates = process_subject(file)
        for cat in category_names:
            rate, sem, _ = subject_rates[cat]
            if not np.isnan(rate):
                all_rates[cat].append(rate)
                all_sems[cat].append(sem)

    # Compute average rate and SEM across subjects
    mean_rates = [np.mean(all_rates[cat]) for cat in category_names]
    mean_sems = [np.std(all_rates[cat], ddof=1) / np.sqrt(len(all_rates[cat])) for cat in category_names]

    print("\n--- Group-Level Correct Response Rate (Mean ± SEM) ---")
    for cat, rate, sem in zip(category_names, mean_rates, mean_sems):
        print(f"{cat}: {rate:.2f}% ± {sem:.2f}")

    # Plotting
    plt.figure(figsize=(8, 6))
    plt.bar(category_names, mean_rates, yerr=mean_sems, capsize=5,
            color=["lightblue", "lightgreen", "lightcoral"], alpha=0.7)
    plt.ylabel("Correct Response Rate (%)")
    plt.title(f"Group-Averaged Correct Response Rate with SEM (n={len(all_files)})")

    for i, rate in enumerate(mean_rates):
        plt.text(i, rate + 2, f"{rate:.2f}%", ha="center", fontsize=10)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
