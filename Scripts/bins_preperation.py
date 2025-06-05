import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import scipy.stats as stats

# Constants
BIN_SIZE = 50  # ms
TIME_RANGE = 500  # ms before/after PlayerShoot
RESPONSE_THRESHOLD = 1000  # ms for valid response after vibration
BIN_EDGES = np.arange(-TIME_RANGE, TIME_RANGE + BIN_SIZE, BIN_SIZE)
NUM_BINS = len(BIN_EDGES) - 1

# Premotor Window
PREMOTOR_START = -120
PREMOTOR_END = -50

# Folder path
folder_path = r"C:/Users/User/PycharmProjects/pythonProject/saiid"
file_list = [f for f in os.listdir(folder_path) if f.startswith("experiment_responses_") and f.endswith(".csv")]

all_bin_correct_rates = []
all_bin_counts = []

for filename in file_list:
    df = pd.read_csv(os.path.join(folder_path, filename), header=None,
                     names=["Timestamp", "Response", "Block", "Experiment", "Unused"], usecols=[0, 1, 2, 3])

    df["Timestamp"] = pd.to_numeric(df["Timestamp"], errors='coerce')
    df.dropna(subset=["Timestamp"], inplace=True)
    df["BaseEvent"] = df["Experiment"].str.extract(r"^(\w+)")

    player_shoots = df[df["BaseEvent"] == "PlayerShoot"]["Timestamp"].values
    vibrations = df[df["BaseEvent"] == "VibrationSent"]
    foot_presses = df[df["BaseEvent"] == "FootPedalPress"]

    bin_correct_counts = np.zeros(NUM_BINS)
    bin_total_counts = np.zeros(NUM_BINS)

    for _, vib_row in vibrations.iterrows():
        vib_time = vib_row["Timestamp"]
        valid_press = foot_presses[
            (foot_presses["Timestamp"] >= vib_time) &
            (foot_presses["Timestamp"] <= vib_time + RESPONSE_THRESHOLD)
        ]
        is_correct = not valid_press.empty

        for shoot_time in player_shoots:
            diff = vib_time - shoot_time
            bin_idx = np.digitize(diff, BIN_EDGES) - 1
            if 0 <= bin_idx < NUM_BINS:
                bin_total_counts[bin_idx] += 1
                if is_correct:
                    bin_correct_counts[bin_idx] += 1

    with np.errstate(divide='ignore', invalid='ignore'):
        bin_correct_rates = np.divide(bin_correct_counts, bin_total_counts, where=bin_total_counts != 0) * 100
        bin_correct_rates[np.isnan(bin_correct_rates)] = 0

    all_bin_correct_rates.append(bin_correct_rates)
    all_bin_counts.append(bin_total_counts)

# Aggregate
all_bin_correct_rates = np.array(all_bin_correct_rates)
all_bin_counts = np.array(all_bin_counts)
mean_correct_rates = np.mean(all_bin_correct_rates, axis=0)
sem_correct_rates = np.std(all_bin_correct_rates, axis=0, ddof=1) / np.sqrt(all_bin_correct_rates.shape[0])
mean_counts = np.mean(all_bin_counts, axis=0).astype(int)

# Export to CSV
df_export = pd.DataFrame({
    "BinStart(ms)": BIN_EDGES[:-1],
    "BinEnd(ms)": BIN_EDGES[1:],
    "MeanRate(%)": mean_correct_rates,
    "SEM": sem_correct_rates,
    "MeanCount": mean_counts
})
df_export.to_csv("mean_correct_response_by_bin.csv", index=False)

# Identify premotor bin index
premotor_mask = (BIN_EDGES[:-1] >= PREMOTOR_START) & (BIN_EDGES[:-1] < PREMOTOR_END)
premotor_bin_index = np.where(premotor_mask)[0]
print(f"Premotor bin index: {premotor_bin_index}")

# ---------------------
# Statistical Analysis
# ---------------------
# One-way repeated-measures ANOVA across bins
f_val, p_val = stats.f_oneway(*[all_bin_correct_rates[:, i] for i in range(NUM_BINS)])

# Paired t-test: Premotor vs. Outside
premotor_means = all_bin_correct_rates[:, premotor_bin_index].mean(axis=1)
outside_index = [i for i in range(NUM_BINS) if i not in premotor_bin_index]
outside_means = all_bin_correct_rates[:, outside_index].mean(axis=1)

t_val, p_ttest = stats.ttest_rel(premotor_means, outside_means)
effect_size = (premotor_means - outside_means).mean() / (premotor_means - outside_means).std(ddof=1)

# Export statistics
stat_summary = pd.DataFrame([{
    "ANOVA_F": round(f_val, 2),
    "ANOVA_p": p_val,
    "T_premotor_vs_outside": round(t_val, 2),
    "T_p": p_ttest,
    "Cohen_d": round(effect_size, 2)
}])
stat_summary.to_csv("correct_response_stats_summary.csv", index=False)

# ---------------------
# Plotting
# ---------------------
x_vals = BIN_EDGES[:-1] + BIN_SIZE / 2
plt.figure(figsize=(12, 6))
plt.errorbar(x_vals, mean_correct_rates, yerr=sem_correct_rates, fmt='o', color='blue',
             ecolor='black', capsize=5, label='Mean Correct Response Rate')

# Annotate vibration counts
for i, (x, y, sem, count) in enumerate(zip(x_vals, mean_correct_rates, sem_correct_rates, mean_counts)):
    plt.text(x, y + sem + 5, str(count), ha='center', fontsize=9)

# Highlight premotor window
plt.axvspan(PREMOTOR_START, PREMOTOR_END, color='gray', alpha=0.3, label='Preparation Window')
plt.axvline(0, color='red', linestyle='--', label='PlayerShoot')
plt.text(-85, 90, "Preparation Window\n(-120 to -50 ms)", ha='center', va='top', fontsize=9, color='black')

plt.xlabel("Time from PlayerShoot (ms)")
plt.ylabel("Correct Response Rate (%)")
plt.title(f"Correct Response Rate Around PlayerShoot (n={all_bin_correct_rates.shape[0]})")
plt.xticks(np.arange(-TIME_RANGE, TIME_RANGE + 1, 500))
plt.ylim(0, 100)
plt.legend()
plt.tight_layout()
plt.show()
