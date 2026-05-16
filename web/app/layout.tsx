import "./globals.css";

import { AppNav } from "../components/nav";

export const metadata = {
  title: "Fraud Ops Console",
  description: "Integration prototype for fraud analyst workflows.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <div className="frame">
            <header className="header">
              <div className="brand">
                <span className="eyebrow">Fraud Operations v1</span>
                <h1 className="title">Analyst Console</h1>
                <p className="subtitle">
                  Case queue, evidence review, rescore, and decision capture over the current FastAPI
                  scoring contract.
                </p>
              </div>
              <AppNav />
            </header>
            <main className="content">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
