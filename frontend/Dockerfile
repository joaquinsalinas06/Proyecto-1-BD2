# Frontend Dockerfile
FROM node:18-alpine

# Establecer directorio de trabajo
WORKDIR /app

# Copiar package.json
COPY package*.json ./

# Instalar dependencias
RUN npm install

# Copiar todo el código del frontend
COPY . .

# Construir la aplicación Next.js
RUN npm run build

# Exponer puerto 3000
EXPOSE 3000

# Comando para ejecutar la aplicación
CMD ["npm", "start"]
