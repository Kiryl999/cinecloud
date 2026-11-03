# Kubernetes

```
k8s/
  cluster/minikube/    once per cluster: Gateway API and Envoy Gateway
  base/                the app and Keycloak, shared by every environment
  overlays/minikube/   the local cluster: PostgreSQL, Redis, the Gateway, local images
```

## Minikube

### Once per cluster

```sh
# Keycloak alone takes about 700 MB
minikube start --cpus 4 --memory 6g
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
  --from-literal=DATABASE_URL="postgresql+asyncpg://cinecloud:$PG_PASSWORD@postgres:5432/cinecloud"
# Keycloak keeps its data in its own database on the same server
kubectl -n cinecloud create secret generic keycloak-secrets \
  --from-literal=KC_DB_PASSWORD="$PG_PASSWORD" \
  --from-literal=KC_BOOTSTRAP_ADMIN_USERNAME=admin \
  --from-literal=KC_BOOTSTRAP_ADMIN_PASSWORD="$(openssl rand -hex 16)"
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

Then open http://localhost - not http://127.0.0.1: passkeys need a domain
name, and Keycloak only redirects back to the addresses its realm lists.
On its first start Keycloak takes about a minute before the sign-in works.

### Keycloak

The admin console is at http://localhost/auth/admin, user `admin`, password:

```sh
kubectl -n cinecloud get secret keycloak-secrets \
  -o jsonpath='{.data.KC_BOOTSTRAP_ADMIN_PASSWORD}' | base64 -d
```

The realm `cinecloud` is imported from `base/cinecloud-realm.json` on the
first start only. Keycloak skips the import once the realm exists, so a later
change to the file has to be made in the console as well.

### Add a cinema and its admin

1. In the admin console, switch to the realm **cinecloud**, then *Users* →
   *Add user*: the e-mail address as username and e-mail, first and last name,
   *Email verified* on, required user action *Webauthn Register Passwordless*.
   Under *Credentials*, set a password with *Temporary* on.
2. Link the account to a new cinema, using the *ID* from its user details:

   ```sh
   kubectl -n cinecloud exec deploy/backend -- python -m scripts.create_tenant \
     --name "Cineplex Bonn" --slug cineplex-bonn --user-id <ID>
   kubectl -n cinecloud exec deploy/backend -- python -m scripts.seed_demo --slug cineplex-bonn
   ```

   A further admin of an existing cinema is linked with
   `python -m scripts.add_admin --slug cineplex-bonn --user-id <ID>`.
3. The admin signs in at http://localhost/admin with the temporary password,
   chooses a new one and registers a passkey. From then on the passkey alone
   is enough.

### Stop and remove

```sh
minikube stop                              # frees the memory, keeps everything
kubectl delete -k k8s/overlays/minikube    # deletes the namespace: app, secrets and database
```
