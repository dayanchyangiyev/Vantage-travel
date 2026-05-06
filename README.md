# Vantage Travel

A modern, AI-powered travel planner built as a comprehensive university project exploring full-stack architecture, software design patterns, and artificial intelligence integration.

## Overview
Vantage Travel is a sophisticated full-stack web application designed to take the friction out of travel planning. Rather than jumping between dozens of tabs to figure out flights, accommodations, and daily activities, Vantage Travel brings everything under one roof. By simply entering a destination, your travel dates, and the number of people going, the app provides a complete, easy-to-digest trip breakdown. 

It works behind the scenes to pull real-time flight and hotel pricing across four different budget tiers (cheapest, affordable, moderate, and luxury), estimates local daily living expenses, and uses artificial intelligence to generate tailored travel tips, packing lists, and a curated daily itinerary. The goal is to provide a seamless, end-to-end planning experience from inspiration to final budgeting.

## Project Organization
To ensure the project remains highly maintainable and scalable, the repository is divided strictly into two main directories, keeping concerns separated:
- **`frontend/`**: Contains the user interface, routing, state management, and client-side API integrations. It is structured to separate visual components from external data fetching logic.
- **`backend/`**: Acts as the central hub of the application. It handles database interactions, secure user authentication, complex external API orchestration, and all core business logic.

## Technologies Used
The application is built using a modern, robust technology stack tailored for speed and reliability:
- **Frontend**: Developed with React 18 and TypeScript for strict type safety, built using the lightning-fast Vite bundler. Styling is handled with Tailwind CSS to keep the design system consistent, while Framer Motion is utilized to create smooth, elegant, and unobtrusive micro-animations.
- **Backend**: Powered by Python 3.14 and the Django 6.x framework. The API layer is constructed with Django REST Framework (DRF) to serve clean JSON endpoints, and user data is stored persistently in SQLite. Authentication relies on secure, stateless JSON Web Tokens (JWT).
- **External Services**: 
  - **SerpAPI**: Queries live data from Google Flights and Google Hotels.
  - **Google Places API**: Used for local living cost estimation (food, transport, activities).
  - **GeoNames**: Provides rapid city search and autocomplete functionality in the user interface.
  - **Google Gemini**: The AI engine responsible for crafting the nuanced, human-like itinerary generation.

## Key Features
- **Dynamic Pricing Engine**: Automatically retrieves live flight and hotel prices, grouping them into four distinct budget tiers so you can instantly see what type of trip matches your financial comfort zone.
- **AI Itinerary Generation**: Crafts custom daily plans, transit protocols, and curated points of interest based on your specific destination and travel window.
- **Budget Evaluation**: Helps you figure out if your planned budget is realistic. The application actively analyzes your input and offers practical suggestions if your budget falls short of your desired travel style.
- **Seamless Saving**: Start planning a trip immediately as a guest. Once you are satisfied with the generated itinerary, you can seamlessly log in or register from the dashboard to securely save the trip to your account without losing any progress.
- **Responsive Interface**: A highly visual, minimalist, and typography-driven dashboard that feels premium. It strips away the clutter usually found on travel sites and works beautifully across desktops, tablets, and mobile devices.

## Design Patterns
This project goes beyond simple scripting by strictly adhering to clean, maintainable architecture. It employs several core software design patterns:
- **MVC (Model-View-Controller)**: Strict separation between the backend data models, the routing controllers, and the React frontend views.
- **Service Layer**: All complex business logic is deliberately isolated in a dedicated service layer on the backend, keeping the API views incredibly lightweight and easy to read.
- **Provider/Strategy**: External data sources use dedicated provider classes. If we want to swap from Google Flights to Skyscanner in the future, the interface remains exactly the same.
- **Façade**: The frontend communicates with the backend and external services through simplified, dedicated functions. This keeps the React components clean and entirely free of messy fetch logic.

## Testing
Reliability is a top priority for this project. The repository includes a robust, automated suite of over 170 unit tests covering both the frontend (using Vitest and React Testing Library) and the backend (using Pytest). 

We enforce a strict rule that all external API calls must be completely mocked during testing. This ensures that our test suite runs in seconds and is entirely predictable, allowing us to verify business logic without exhausting real-world API rate limits or relying on network stability.

## Future Plans
As a university project, Vantage Travel serves as a strong architectural foundation with plenty of room to grow. We plan to expand the application into a more interactive and capable assistant. Potential future functionalities include:

- **AI Agent Integration**: Evolving the application from a planner into a fully autonomous agent that can actively book flights, reserve hotel rooms, and handle cancellations automatically on the user's behalf.
- **Flight and Hotel Suggestion Options**: Providing intelligent, interactive lists of alternative flight routes and hotel recommendations, allowing the user to swap out default suggestions for options that better fit their specific schedule or loyalty programs.
- **Interesting Places Menu**: An interactive, map-based menu that lets users visually explore local attractions, restaurants, and hidden gems around their destination, making it easier to customize their AI-generated itinerary.
- **Simple Tasks & Checklists**: Integrating a built-in trip management system where users can organize pre-trip tasks (e.g., "Renew passport", "Buy travel insurance", "Pack adapters") to ensure nothing is forgotten before departure.
