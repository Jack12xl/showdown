import numpy as np
import matplotlib.pyplot as plt 
import math

if __name__ == "__main__":

	gap = 50
	up = 1201
	down = 1000
	length = math.ceil((up-down)/gap)

	rank = np.arange(down,up,gap)
	count = np.zeros([length])
	sum_ = np.zeros([length])
	file = "record.txt"
	with open(file, 'r') as f:
		lines = f.readlines()
		for line in lines:
			w, s = line.split(' ')
			r = int(s.split('.')[0])
			win = w == 'win'
			for i in range(rank.shape[0]-1):
				if rank[i+1]>r:
					count[i] += win
					sum_[i] += 1
					break

	rate = np.zeros([length])
	for i in range(rank.shape[0]):
		rate[i] = count[i]/sum_[i]

	plt.plot(rank,rate)
	plt.show()


