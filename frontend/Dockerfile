# Build étape
FROM node:20 AS build

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

# Serveur statique
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80