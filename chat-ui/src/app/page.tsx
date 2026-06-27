"use client";

import { CopilotChat } from "@copilotkit/react-ui";

export default function Page() {
  return (
    <main className="flex h-screen flex-col">
      <header className="border-b border-white/10 px-6 py-4">
        <h1 className="text-xl font-semibold text-white">
          Financial AI Advisor
        </h1>
        <p className="text-sm text-white/50">
          Powered by Google ADK + CopilotKit
        </p>
      </header>
      <div className="flex-1">
        <CopilotChat
          labels={{
            title: "Financial Advisor",
            initial:
              "Ask me about stocks, alternative investments, career ROI, or portfolio allocation.",
            placeholder: "e.g. Analyze Apple stock, or Should I get a GCP cert?",
          }}
          className="h-full"
        />
      </div>
    </main>
  );
}
