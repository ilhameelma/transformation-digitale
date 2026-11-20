# Étape 1 : Construire l'application React
FROM node:20-alpine as build

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Étape 2 : Servir l'application avec Nginx (léger et rapide)
FROM nginx:alpine

# Copier le résultat du build dans le dossier servi par Nginx
COPY --from=build /app/dist /usr/share/nginx/html

COPY nginx.conf /etc/nginx/conf.d/default.conf
# Exposer le port 80 (interne au conteneur)
EXPOSE 80