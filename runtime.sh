# Installation commands and instructions:

# Docker commands
docker network create mynet

docker build -t frontend:v1 .
docker build -t app:v1 .
docker run -dit --name frontend --network mynet -p 8080:80  frontend:v1
docker run -dit --name backend --network mynet -p 8000:8000 backend
docker run -dit --name mongodb --network mynet -p 27017:27017 -v mongo_data:/data/db mongo:6.0


# Installing Grafana and prometheus
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install monitoring prometheus-community/kube-prometheus-stack -n monitoring --create-namespace
kubectl port-forward svc/monitoring-kube-prometheus-prometheus -n monitoring 9090
kubectl port-forward svc/monitoring-grafana -n monitoring 3000:80

# Read me

helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

helm install loki grafana/loki -f values.yaml

# Loki
kubectl port-forward --namespace monitoring svc/loki-gateway 3100:80 &
http://loki-gateway.monitoring.svc.cluster.local/

helm upgrade --install loki grafana/loki \
  --namespace monitoring \
  -f values.yaml

http://loki-gateway.monitoring.svc.cluster.local/

kubectl port-forward --namespace monitoring svc/loki 3101:3100 &
kubectl --namespace monitoring port-forward daemonset/promtail 3101

helm install promtail grafana/promtail \
  --namespace monitoring \
  --set loki.serviceName=loki