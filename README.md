# Motorcycle Weather API

A FastAPI-based weather forecasting service that provides weather data for motorcycle routes.
 
## Architecture

- **FastAPI**: Web framework for the REST API
- **Google Firestore**: NoSQL database for caching weather data with automatic TTL
- **Weather.gov API**: Source for weather forecast data
- **Google Routes API**: For route calculation

## Features

- Get weather forecasts for specific coordinates
- Get weather forecasts along a route between two locations - **Feature in development**
- Automatic caching with expiration to minimize API calls
- Serverless, scalable architecture with Firestore 
