1. frontpage [POD] - graph visualizer, p2 strategy -> configure, schedules, playground
3. k8s [INFRA]
4. p2-strategy-pod [POD]-> interacts with haxproxy 
	1. configure -> stores the config result in the database and sends the succesfull callback signal
		a. configure also calls many worker pod to calculate the result
		b. it first call the ingester to refill the db with latest stocks data
	2. this pod also have various other api recursive logic that does the interaction with database
	3. p2-scheduler -> it creates a scheduler schema with the also the sechedle data 
	4. p2-runner -> responsible for the run of a schedule. It can be argo job - tbd. It also interacts with the 	ingester or broker if needed to make the transaction and will keep the db schedule updated.
	5. playground -> interactive graph based p2 strategy visualizer
5. Ingester [POD] -> fills the data into db and have a lock
6. Broker [POD] -> for creating the transaction and reading the stocks data
7. DB and DBwriter [PODS] -> db layer
8. Graph Visualizer [POD] -> for search,filter and finding the stock performace
9. Ingress / HProxy -> public routing
                 (public)

