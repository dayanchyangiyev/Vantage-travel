# Environment Variables (No Secrets)

Use these keys in `.env/.env` and provide your own values.

```env
# Django core
# DJANGO_SECRET_KEY= (Optional in dev, defaults to insecure key)
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
CORS_ALLOW_ALL_ORIGINS=True

# External services
GEONAMES_USERNAME=
GOOGLE_MAPS_API_KEY=

# SerpAPI (flights/hotels)
SERPAPI_BASE_URL=https://serpapi.com/search.json
SERPAPI_API_KEY=

# Google Places (local daily living costs)
GOOGLE_PLACES_TEXT_SEARCH_URL=https://places.googleapis.com/v1/places:searchText
GOOGLE_PLACES_API_KEY=
```
