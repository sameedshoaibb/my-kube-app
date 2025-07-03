docker network create mynet

docker build -t frontend:v1 .
docker build -t app:v1 .

docker run -dit --name frontend --network mynet -p 8080:80  frontend:v1
docker run -dit --name backend --network mynet -p 8000:8000 backend
docker run -dit --name mongodb --network mynet -p 27017:27017 -v mongo_data:/data/db mongo:6.0

