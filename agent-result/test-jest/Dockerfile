FROM node:18-slim

WORKDIR /app
RUN git clone https://github.com/facebook/jest.git .
RUN npm install
RUN npm test

CMD ["/bin/bash"]