FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json ./
RUN npm install

FROM deps AS dev
WORKDIR /app
COPY . .
CMD ["npm", "run", "dev"]
