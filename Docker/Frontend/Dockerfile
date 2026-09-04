FROM node:22-alpine AS build

WORKDIR /app

COPY Frontend/package*.json ./

RUN npm ci

COPY Frontend/ .

RUN npm run build -- --configuration production


FROM nginx:alpine

COPY --from=build /app/dist/ /usr/share/nginx/html/