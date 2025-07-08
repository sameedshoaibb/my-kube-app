docker network create mynet

docker build -t frontend:v1 .
docker build -t app:v1 .

docker run -dit --name frontend --network mynet -p 8080:80  frontend:v1
docker run -dit --name backend --network mynet -p 8000:8000 backend
docker run -dit --name mongodb --network mynet -p 27017:27017 -v mongo_data:/data/db mongo:6.0



#


# Installing Grafana and prometheus
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install monitoring prometheus-community/kube-prometheus-stack -n monitoring --create-namespace
kubectl port-forward svc/monitoring-kube-prometheus-prometheus -n monitoring 9090
kubectl port-forward svc/monitoring-grafana -n monitoring 3000:80