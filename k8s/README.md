# Kubernetes

```
k8s/
  cluster/minikube/    once per cluster: Gateway API and Envoy Gateway
  base/                the app, shared by every environment
  overlays/minikube/   the local cluster: PostgreSQL, Redis, the Gateway, local images
```

## Minikube

### Once per cluster

```sh
minikube start --cpus 4 --memory 4g
kubectl apply --server-side -k k8s/cluster/minikube
kubectl wait --timeout=5m -n envoy-gateway-system deployment/envoy-gateway --for=condition=Available
```

### Secrets

Created once by hand; they never go into git.

```sh
kubectl create namespace cinecloud
PG_PASSWORD=$(openssl rand -hex 24)
kubectl -n cinecloud create secret generic postgres-secrets \
  --from-literal=POSTGRES_PASSWORD="$PG_PASSWORD"
kubectl -n cinecloud create secret generic backend-secrets \
  --from-literal=DATABASE_URL="postgresql+asyncpg://cinecloud:$PG_PASSWORD@postgres:5432/cinecloud" \
  --from-literal=JWT_SECRET="$(openssl rand -hex 32)"
unset PG_PASSWORD
```

### Deploy

The first time, and again after every code change:

```sh
docker build -t cinecloud-backend:dev backend
docker build -t cinecloud-frontend:dev frontend
minikube image load cinecloud-backend:dev cinecloud-frontend:dev

# a Job cannot be changed, only replaced
kubectl -n cinecloud delete job migrate --ignore-not-found
kubectl apply -k k8s/overlays/minikube
kubectl -n cinecloud wait --for=condition=complete job/migrate --timeout=5m

# the tag stays "dev", so the pods must be told to load the new image
kubectl -n cinecloud rollout restart deployment/backend deployment/frontend
```

On a fresh cluster the first migration attempts fail until PostgreSQL accepts
connections; the Job retries by itself.

### Open the app

```sh
minikube tunnel    # in its own terminal; asks for sudo because of port 80
```

Then open http://127.0.0.1.

### Operator scripts

```sh
kubectl -n cinecloud exec deploy/backend -- python -m scripts.create_tenant \
  --name "Cineplex Bonn" --slug cineplex-bonn --email admin@cineplex-bonn.de --password secret123
kubectl -n cinecloud exec deploy/backend -- python -m scripts.seed_demo --slug cineplex-bonn
```

### Stop and remove

```sh
minikube stop                              # frees the memory, keeps everything
kubectl delete -k k8s/overlays/minikube    # deletes the namespace: app, secrets and database
```
