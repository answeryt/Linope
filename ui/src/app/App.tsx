import { type ReactNode, useState } from "react";
import { useRoute } from "@/app/router";
import { Menu } from "@/components/docs/icons";
import { SiteFooter } from "@/components/docs/site-footer";
import { SiteSidebar } from "@/components/docs/site-sidebar";
import { ComponentDocPage } from "@/pages/component-doc-page";
import { InstallationPage } from "@/pages/installation";
import { IntroductionPage } from "@/pages/introduction";
import { PlaygroundPage } from "@/pages/playground";

function resolvePage(route: string): ReactNode {
  if (route === "/docs/installation") {
    return <InstallationPage />;
  }
  if (route === "/playground") {
    return <PlaygroundPage />;
  }
  const component = route.match(/^\/docs\/components\/([a-z0-9-]+)$/);
  if (component) {
    return <ComponentDocPage key={component[1]} slug={component[1]} />;
  }
  return <IntroductionPage />;
}

function App() {
  const route = useRoute();
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <div className="min-h-screen bg-background">
      <button
        aria-label="Open navigation"
        className="glass-chip fixed top-4 left-4 z-40 flex size-9 cursor-pointer items-center justify-center rounded-full text-foreground lg:hidden"
        onClick={() => setMenuOpen(true)}
        type="button"
      >
        <Menu className="size-5" />
      </button>
      <div className="mx-auto flex max-w-[1200px] px-4 lg:px-6">
        <SiteSidebar onClose={() => setMenuOpen(false)} open={menuOpen} />
        <main className="min-w-0 flex-1 py-10 lg:pl-10">
          {resolvePage(route)}
          <SiteFooter />
        </main>
      </div>
    </div>
  );
}

export { App };
