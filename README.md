# AlgoTrade Pro

An asynchronous algorithmic trading simulator backend built with Python and FastAPI.

## Project Overview

AlgoTrade Pro is a simulated financial trading platform that allows users to manage virtual wallets, monitor financial assets, execute buy/sell trades, and track transaction history.

## Technology Stack

- Python 3.10+
- FastAPI
- PostgreSQL
- SQLAlchemy 2.0
- Pydantic v2
- JWT Authentication
- HTTPX
- WebSockets
- Pytest

## Core Features

- User authentication and authorization
- Virtual wallet management
- Stock and cryptocurrency asset management
- Simulated buy and sell operations
- Transaction ledger
- External market price integration
- Transaction integrity and concurrency control
- Real-time price streaming
- Automated testing

## Architecture

The application follows a modular layered architecture.

- core: Configuration, security and database setup
- models: Database entities
- schemas: Request and response validation
- services: Business logic
- repositories: Data access
- api: REST API endpoints
- websocket: Real-time communication
- tests: Automated quality assurance

## Development Status

Day 1 - Project initialization and architecture setup.

## Disclaimer

This project is an educational trading simulator. It does not execute real financial trades or provide investment advice.
