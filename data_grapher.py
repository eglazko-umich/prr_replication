import matplotlib.pyplot as plt

datafile = "experiment_1_data.txt"


data = []
with open(datafile, 'r') as f:
	for line in f:
		data.append(float(line.strip()))

plt.hist(data, bins=50, color="blue", edgecolor="black")

plt.xlabel("Outage Duration")
plt.ylabel("Frequency")
plt.title("PRR Test Replication")

plt.show()