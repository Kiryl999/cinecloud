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

### Passwords

There are none to make: the overlay brings fixed ones, in plain text in
`overlays/minikube/kustomization.yml`. That is fine for a cluster that only
this machine reaches, and only for that.

### Deploy

Argo CD deploys the app from main on GitHub, not from the local checkout,
and creates the namespace `cinecloud` for it. Hand it the app:

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

The admin console is at http://localhost/auth/admin, user `admin`, password
`admin`.

The realm `cinecloud` is imported from `base/cinecloud-realm.json` on the
first start only. Keycloak skips the import once the realm exists, so a later
change to the file has to be made in the console as well - or Keycloak starts
over from the file, which deletes every account of the realm:

```sh
kubectl -n cinecloud exec postgres-0 -- psql -U cinecloud -d postgres -c 'DROP DATABASE keycloak WITH (FORCE)'
kubectl -n cinecloud delete pod -l app.kubernetes.io/name=keycloak
```

Admins linked to a cinema then have to register and be linked again.

The file lists all of Keycloak's required actions, since a list there replaces
Keycloak's own as a whole. The one change: every new account has to register
a passkey.

### Add a cinema and its admin

Admins have no password, only a passkey.

1. Open http://localhost/admin, choose *Register* on the sign-in page and
   enter an e-mail address and a name. The browser then creates the passkey,
   with Windows Hello, Touch ID or a phone. Until the next step the app
   answers that the account is not linked to a cinema.
2. Link the account to a new cinema, using its *ID* from the admin console
   (realm **cinecloud**, *Users*):

   ```sh
   kubectl -n cinecloud exec deploy/backend -- python -m scripts.create_tenant \
     --name "Cineplex Bonn" --slug cineplex-bonn --user-id <ID>
   kubectl -n cinecloud exec deploy/backend -- python -m scripts.seed_demo --slug cineplex-bonn
   ```

   A further admin of an existing cinema is linked with
   `python -m scripts.add_admin --slug cineplex-bonn --user-id <ID>`.
3. Open http://localhost/admin again. From then on the passkey signs the
   admin in.

Anyone who reaches the sign-in page can register, but an account can do
nothing until it is linked to a cinema. Where others can reach Keycloak,
registration would be closed and admins invited by e-mail instead.

### Stop and remove

```sh
minikube stop                                    # frees the memory, keeps everything
kubectl -n argocd delete application cinecloud   # deletes the app; the database stays
kubectl delete namespace cinecloud               # and that as well
```

Deleting the app with `kubectl delete -k` would not last: Argo CD puts back
whatever its Application still lists.
