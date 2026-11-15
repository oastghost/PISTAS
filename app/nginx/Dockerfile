# Build context is app. Builds the frontend and serves it with the proxy.
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine
RUN apk add --no-cache openssl
COPY --from=web /web/dist /usr/share/nginx/html
COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY nginx/10-selfsigned.sh /docker-entrypoint.d/10-selfsigned.sh
RUN chmod +x /docker-entrypoint.d/10-selfsigned.sh
