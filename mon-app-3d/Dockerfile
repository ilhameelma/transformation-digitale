# Étape 1 : Construire l'application React
FROM node:20-alpine as build

WORKDIR /app
COPY package*.json ./
RUN npm install --fetch-timeout=600000 --fetch-retries=5
COPY . .
RUN npm run build

# Étape 2 : Servir l'application avec Nginx
FROM nginx:alpine

# Copier le résultat du build
COPY --from=build /app/dist /usr/share/nginx/html

# Copier la config Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80