FROM node:22-alpine AS frontend-build

WORKDIR /app

COPY Frontend/package*.json ./

RUN npm ci

COPY Frontend/ .

RUN npm run build -- --configuration production


FROM nginx:alpine

COPY --from=frontend-build /app/dist/ /usr/share/nginx/html/

COPY Docker/nginx/nginx.conf /etc/nginx/nginx.conf