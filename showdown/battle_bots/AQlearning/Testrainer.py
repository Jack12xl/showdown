from trainer import QlearningTrainer, Counter

class TestTrainer(QlearningTrainer):
	def getFeatures(self, state, action):
		features = Counter()
		features['f1'] = state['s1']
		features['f2'] = state['s2']
		features['f3'] = action
		return features

	def getRewards(self, **args):
		newState=args['newState']
		reward = newState['s1'] + newState['s2']
		return reward

	def getLegalactions(self, state):
		return [1,2]

if __name__ == '__main__':
	test = TestTrainer(alpha=1.0, epsilon=0.5, gamma=1.0)
	state1 = {
		's1':1,
		's2':2
	}
	state2 = {
		's1':2,
		's2':2
	}
	test.update(state1, 2, state2, newState = state2)
	print(test.weights)
