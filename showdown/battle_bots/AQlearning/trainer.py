from abc import abstractmethod


class Counter(dict):
	def __getitem__(self, idx):
		self.setdefault(idx, 0)
		return dict.__getitem__(self, idx)

	def totalCount(self):
		return sum(self.values())

	def copy(self):
		return Counter(dict.copy(self))

	def __mul__(self, y ):
		sum = 0
		x = self
		if len(x) > len(y):
			x,y = y,x
		for key in x:
			if key not in y:
				continue
			sum += x[key] * y[key]
		return sum

	def __add__(self, y):
		s = set()
		for i in self:
			s.add(i)
		for i in y:
			s.add(i)

		n = Counter()
		for i in s:
			n[i] = self[i] + y[i]
		return n

	def mul(self, y):
		for key in self:
			self[key] *= y
		return self



class Trainer:
	def __init__(self, alpha=1.0, epsilon=0.5, gamma=0.8):
		"""
		alpha	- learning rate
		epsilon  - exploration rate
		gamma	- discount factor
		"""
		self.alpha=float(alpha)
		self.epsilon=float(epsilon)
		self.discount=float(gamma)

	@abstractmethod
	def getQValue(self, state, action):
		...

	@abstractmethod
	def getValue(self, state):
		...

	@abstractmethod
	def update(self, state, action, nextState, rewards):
		...

class QlearningTrainer(Trainer):
	def __init__(self, **args):
		Trainer.__init__(self, **args)
		self.weights = Counter()

	@abstractmethod
	def getFeatures(self, state, action):
		#return a counter
		...

	@abstractmethod
	def getRewards(self, **args):
		...

	@abstractmethod
	def getLegalActions(self, state):
		#get a list of actions
		...

	def getQValue(self, state, action):
		return self.getFeatures(state, action)*self.weights

	def getValue(self, state):
		if not self.getLegalActions(state):
			return 0.0
		maxValue = -float("inf")
		for action in self.getLegalActions(state):
			if self.getQValue(state, action) > maxValue:
				maxValue = self.getQValue(state, action)
		return maxValue

	def update(self, state, action, nextState, **args):
		reward = self.getRewards(**args)
		diff = reward + self.discount * self.getValue(nextState) - self.getQValue(state, action)
		features = self.getFeatures(state, action)
		for feature in features.keys():
		  self.weights[feature] = self.weights[feature] + self.alpha * diff * features[feature]
