FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ENV API_URL=http://backend:8000
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
