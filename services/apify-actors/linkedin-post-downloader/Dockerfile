# Use Apify's Node 18 image with Playwright
FROM apify/actor-node-playwright-chrome:18

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install --production

# Copy source
COPY . ./

# Run the actor
CMD ["npm", "start"]
