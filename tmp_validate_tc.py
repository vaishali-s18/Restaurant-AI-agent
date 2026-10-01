import random
from restaurant_order_agent import RestaurantOrderAgent

agent = RestaurantOrderAgent(menu={'burger':10,'pizza':30,'momos':3,'colddrink':2,'pasta':1})
print('extract 20 burgers ->', agent._extract_order('I want 20 burgers'))
print('extract 2 pizzas ->', agent._extract_order('I want 2 pizzas'))
print('extract 5 coffee ->', agent._extract_order('I want 5 coffee'))
print('process 20 burgers ->', agent.process('I want 20 burgers'))

print('--- TC1 ---')
agent = RestaurantOrderAgent(menu={'burger':10,'pizza':30,'momos':3,'colddrink':2,'pasta':1})
print('Q1', agent.process('What is the capital of France?'))
print('P1', agent.process('I want 20 burgers'))
print('P2', agent.process('I want 5 coffee'))
print('P3', agent.process('I want 5 coffee'))

print('--- TC2 ---')
agent = RestaurantOrderAgent(menu={'burger':10,'pizza':30,'momos':3,'colddrink':2,'pasta':1}, cook_success_prob=0.6, serve_success_prob=0.6)
vals = iter([0.9, 0.9, 0.2, 0.2])
random.random = lambda: next(vals)
print('S1', agent.process('I want 2 pizzas'))
random.random = lambda: 0.5

print('--- TC3 ---')
agent = RestaurantOrderAgent(menu={'burger':10,'pizza':30,'momos':3,'colddrink':2,'pasta':1}, cook_success_prob=0.6, serve_success_prob=0.6)
vals = iter([0.9, 0.2, 0.9, 0.2, 0.9])
random.random = lambda: next(vals)
print('T3A', agent.process('I want 20 burgers'))
print('T3B', agent.process('I want 2 pizzas'))
random.random = lambda: 0.5
