# BlackBox Regulatory Guardian - UI

This is the frontend dashboard for the Agentic AI Platform, built with React, Vite, Tailwind CSS, and Zustand. It provides a dynamic, premium UI for interacting with contracts, regulatory updates, and the AI Compliance Agent.

## Prerequisites
- Node.js (v18+)
- npm or yarn

## Setup & Installation

Navigate to the `UI` directory and install the dependencies:
```bash
npm install
```

## Running the Frontend

Start the Vite development server:
```bash
npm run dev
```
The application will be available at `http://localhost:5173`.

## Architecture Overview
- **`src/components/ContractDashboard.jsx`**: Interface for uploading PDFs and viewing the list of processed contracts.
- **`src/components/ContractViewer.jsx`**: Visualizes the PDF alongside extracted clauses, risks, and XAI/SHAP explanations.
- **`src/components/LRRDashboard.jsx`**: Displays regulatory feeds and automated policy impact mappings.
- **`src/components/AgentChat.jsx`**: Chat interface communicating with the LangGraph/MCP backend agent.
- **`src/store/useStore.js`**: Zustand store for managing global application state.

## Debugging Guide

1. **Backend Connectivity**:
   If the frontend is unable to fetch data, ensure the FastAPI backend is running on `http://localhost:8000`. Check the browser's Developer Tools (Network tab) for CORS errors or failed requests.

2. **Tailwind CSS Not Applying**:
   Ensure `vite.config.js` and `tailwind.config.js` are properly configured. If styles seem broken, restart the dev server: `npm run dev`.

3. **State Management Issues**:
   If UI elements aren't updating (e.g., uploading a contract doesn't show in the list), inspect the Zustand store. You can use React DevTools to inspect the `useStore` hook.

4. **PDF Viewer Errors**:
   If the PDF fails to load or highlights are misaligned, ensure the PDF file is valid and check the console for `react-pdf-highlighter` specific warnings.
