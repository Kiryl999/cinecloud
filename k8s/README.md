# Kubernetes

```
k8s/
  cluster/minikube/    once per cluster: Gateway API, Envoy Gateway and Argo CD
  base/                the app and Keycloak, shared by every environment
  overlays/minikube/   the local cluster: PostgreSQL, Redis, the Gateway, images from ghcr.io
  apps/minikube/       the Argo CD Application that deploys overlays/minikube
```

## Minikube

### Once per cluster

```sh
# Keycloak alone takes about 700 MB
minikube start --cpus 4 --memory 6g
kubectl apply --server-side -k k8s/cluster/minikube
kubectl wait --timeout=5m -n envoy-gateway-system deployment/envoy-gateway --for=condition=Available
kubectl wait --timeout=5m -n argocd deployment --all --for=condition=Available
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

Argo CD deploys the app from main on GitHub, not from the local checkout.
Once the secrets are there, hand it the app:

```sh
kubectl apply -f k8s/apps/minikube
```

From then on there is nothing to run. CI builds both images after every push
to main, pushes them to ghcr.io and commits their tag to
`overlays/minikube/images/`. Argo CD looks at main every two to three minutes
and syncs what changed: the migration first, then the backend (see
`base/migrate-job.yml` for the order).

```sh
kubectl -n argocd get application cinecloud    # SYNC STATUS and HEALTH
kubectl -n cinecloud get pods
```

HEALTH stays *Progressing* until `minikube tunnel` runs: Argo CD counts the
Gateway as up only once it has an address.

### Argo CD

The web UI shows every resource of the app, its sync history and the diff
against git:

```sh
kubectl -n argocd port-forward svc/argocd-server 8443:443
```

Then open https://localhost:8443 (a self-signed certificate), user `admin`,
password:

```sh
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d
```

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
minikube stop                                    # frees the memory, keeps everything
kubectl -n argocd delete application cinecloud   # deletes the app; secrets and database stay
kubectl delete namespace cinecloud               # and those as well
```

Deleting the app with `kubectl delete -k` would not last: Argo CD puts back
whatever its Application still lists.
