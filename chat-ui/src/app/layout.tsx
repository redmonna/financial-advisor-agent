"use client";

import { CopilotKit } from "@copilotkit/react-core";
import "@copilotkit/react-ui/styles.css";
import "./globals.css";
import { useState } from "react";
import { AgentSelector } from "@/components/AgentSelector";

const AGENTS = [
  {
    id: "financial_advisor",
    name: "Financial Advisor",
    description: "Stocks, investments, career ROI, and portfolio analysis",
    icon: "📊",
  },
  // Add more agents here as you build them
];

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [activeAgent, setActiveAgent] = useState(AGENTS[0].id);

  return (
    <html lang="en">
      <body className="antialiased">
        <CopilotKit runtimeUrl="/api/copilotkit" agent={activeAgent}>
          <div className="flex h-screen">
            <AgentSelector
              agents={AGENTS}
              activeAgent={activeAgent}
              onSelect={setActiveAgent}
            />
            <div className="flex-1">{children}</div>
          </div>
        </CopilotKit>
      </body>
    </html>
  );
}
