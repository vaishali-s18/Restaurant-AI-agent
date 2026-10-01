I am building a restaurant order management AI agent system using langgraph.
I will explain you very clearly what i want and what is the architecture. I will also explain you the nodes, the states and the edges. In the end i will provide you test cases to stimulate and to tell me whether they pass or not.

The rough plan is as follows:

There will be a user, when the code runs the user will give an order. This will be taken as an input which i will type. This order should go to the LLM the order as of now should contain dish and required quantities.

for simplicity purpose for now we will limit the order to one particular dish and whatever quantity the user wants. The LLM has to extract the order name and the quantity from the user input.

If the user input is unrelated to Food ordering, the LLM should not process that and tell the user the same thing that is I am an AI ordering agent of Food Ordering and not a General purpose LLM.

Once the LLM has order dish and quantity. It will send to a node called order_confirmed.
The task of this order_confirmed is to look at the menu (I will tell you the menu later in this prompt) then this node will decide one of 3 case.
The order is available
the order is partially available means quantity is not sufficient
the order is not available at all( dish being not in the menu or 0 quantity available).
it will put this in the status of the state(I will tell you the exact content of the langgraph state as well).

once the LLM recieved this
if teh status is confirmed(full available ) it should call another node called cook.
if teh status is partial or not available it should again prompt the user to decide.
the user can either place a new order or can confirm if he wants to go ahead with the partial order.

this order retries will be limited to 3 attempts meaning if after 3 attempts the user is not satisfied the system will come to teh end node.

when teh cook node is called tehre can be two cases, either the cook is done tehn teh status will eb ready
if teh cook fails  (we can usee a prev function). Give 40 % chance of fail and 60% chance of success.

if teh cook fails tehre should be 1 more attempt allowed for cook to succeed. if teh cook fails even after these then llm should issue an appology to teh user and come to end state


if teh cook suceeds tehn teh status will be read
and the next ndoe will be called which is serve
similarly this also has 2 cases.
Serve pass or Serve fail

this alsoe has 2 retry attempt
if teh serve fails 2 times then teh llm should end state 
if teh serve succeed teh status should become complete ans the llm should  issue a message to the user saying your order is complete. if serve fails cook shoudk be called one more time  to retry.
Note that if teh cook has exhausted its retry attempts then it should not cook again and llm should issue an appology and come to end state


Now teh state of langgraph: 
Tehre should be a annotated message betweeen llm and user tehre should be order details 
dish name as str 
required quantity as int
available quantity as str
order_confirmed will write teh available quantity by reading teh menu

the llm should get to know the order confirm status by reading teh state
if a dish is not available in the menu tehn orderconfirm should write 0 as avail quanatity

tehn there should be a status 
each node will updsate teh status as specified in above rules
then order retry attempt which are 3 
cook retry attempts which are 2
serve retry attemps which are 2 
each tiem a failure happens and a node is retrying it should decrement the counter
if any retry counter becomes 0 it means it is over.llm should understand whether it should give a retry or issue appology by reading this counter.
in teh end tehre should be final result , whether teh order is completed or not.


This is the menu 
burger 10
pizza 30
momos 3
colddrink 2
pasta 1

Write the code  and ask if there are any open questions from your side then ask
i will give you test scenarios to test

TC 1 : 
a user asks unrelated question 
then he places a order which is partial 
then he rejects teh partial and wants to order again 
again he orders a dish which is not available
expected: END due to order retry 

TC 2: 
user place an order which can be availabel 
cook makes it fails once
serve fails once
cook retries success
serve does success 
overall success

TC 3:
user order partial 
doesnot want partial
order again fuly availaable
cook makes it fails 
makes again success
serve fails
cook retries success
serve fails again 
cook does not retry due to retries exhaust 
overall failure