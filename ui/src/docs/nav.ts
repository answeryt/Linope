interface NavItem {
  title: string;
  to: string;
}

interface NavGroup {
  items: NavItem[];
  title: string;
}

const NAV: NavGroup[] = [
  {
    title: "Getting Started",
    items: [
      { title: "Introduction", to: "/" },
      { title: "Installation", to: "/docs/installation" },
      { title: "Playground", to: "/playground" },
    ],
  },
  {
    title: "Components",
    items: [
      { title: "Glass", to: "/docs/components/glass" },
      { title: "Button", to: "/docs/components/glass-button" },
      { title: "Dialog", to: "/docs/components/glass-dialog" },
      { title: "Dock", to: "/docs/components/glass-dock" },
      { title: "Input", to: "/docs/components/glass-input" },
      { title: "Popover", to: "/docs/components/glass-popover" },
      { title: "Slider", to: "/docs/components/glass-slider" },
      { title: "Switch", to: "/docs/components/glass-switch" },
      { title: "Tabs", to: "/docs/components/glass-tabs" },
      { title: "Tooltip", to: "/docs/components/glass-tooltip" },
    ],
  },
];

const REGISTRY_BASE = "https://loreglasses.com/r";
const REGISTRY_NAMESPACE = "@lore-glass";
const REGISTRY_TEMPLATE = `${REGISTRY_BASE}/{name}.json`;

export { NAV, REGISTRY_BASE, REGISTRY_NAMESPACE, REGISTRY_TEMPLATE };
export type { NavGroup, NavItem };
