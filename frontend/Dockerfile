# syntax=docker/dockerfile:1

# The build output is plain HTML, JS and CSS, the same for every CPU, so this
# stage always runs on the build machine's own platform: a multi-platform
# build then does not have to emulate npm and vite for the other one.
FROM --platform=$BUILDPLATFORM node:22-alpine AS build

WORKDIR /app

# dependencies before the code: npm ci runs again only when the lock changes
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci

COPY . .
RUN npm run build


# Serves the static files only; /api never reaches this container because the
# ingress routes it to the backend. User (uid 101) and start command come from
# the base image, which needs no root and therefore listens on 8080.
FROM nginxinc/nginx-unprivileged:1.30-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080
