import { Close } from "@/components/docs/icons";
import { Link, useRoute } from "@/app/router";
import { NAV } from "@/docs/nav";
import { cn } from "@/lib/utils";

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const route = useRoute();
  return (
    <nav className="flex flex-col gap-6">
      {NAV.map((group) => (
        <div key={group.title}>
          <div className="px-2.5 font-semibold text-[13px] text-foreground">
            {group.title}
          </div>
          <div className="mt-1.5 flex flex-col gap-0.5">
            {group.items.map((item) => {
              const active = route === item.to;
              return (
                <Link
                  className={cn(
                    "rounded-lg px-2.5 py-1.5 text-[13.5px] transition-colors",
                    active
                      ? "bg-accent font-medium text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                  key={item.to}
                  onClick={onNavigate}
                  to={item.to}
                >
                  {item.title}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );
}

function SiteSidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <>
      <aside className="sticky top-0 hidden h-screen w-56 shrink-0 overflow-y-auto py-10 pr-6 lg:block">
        <NavLinks />
      </aside>
      {open ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            aria-label="Close navigation"
            className="absolute inset-0 bg-black/40"
            onClick={onClose}
            type="button"
          />
          <div className="absolute top-0 bottom-0 left-0 w-72 overflow-y-auto bg-background p-5 shadow-xl">
            <div className="mb-5 flex items-center justify-end">
              <button
                aria-label="Close navigation"
                className="flex size-8 items-center justify-center rounded-full text-muted-foreground hover:text-foreground"
                onClick={onClose}
                type="button"
              >
                <Close className="size-5" />
              </button>
            </div>
            <NavLinks onNavigate={onClose} />
          </div>
        </div>
      ) : null}
    </>
  );
}

export { SiteSidebar };
