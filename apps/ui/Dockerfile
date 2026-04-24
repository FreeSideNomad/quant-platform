FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate
COPY pnpm-lock.yaml* ./
RUN pnpm install
COPY . .
RUN pnpm build

FROM nginx:1.27-alpine
RUN apk add --no-cache curl
COPY --from=build /app/dist /usr/share/nginx/html
COPY <<'NGINX' /etc/nginx/conf.d/default.conf
server {
    listen 5173;
    location / {
        root /usr/share/nginx/html;
        try_files $uri /index.html;
    }
    location /api/ {
        proxy_pass http://api:8000/;
    }
}
NGINX
EXPOSE 5173
CMD ["nginx", "-g", "daemon off;"]
