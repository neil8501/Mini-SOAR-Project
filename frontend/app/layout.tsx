import "./globals.css";
import TopNav from "@/components/TopNav";

export const metadata = {
  title: "Mini-SOAR",
  description: "Local SOAR-style incident automation platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="min-h-screen">
          <TopNav />
          <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
        </div>
      </body>
    </html>
  );
}