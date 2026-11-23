import { CodeBlock } from "@/components/docs/code-block";
import { DocPage, DocProse, DocSection } from "@/components/docs/doc-page";
import { InstallTabs } from "@/components/docs/install-tabs";
import { REGISTRY_NAMESPACE, REGISTRY_TEMPLATE } from "@/docs/nav";

const usage = `import { Glass } from "@/components/ui/glass";
import { GlassButton } from "@/components/ui/glass-button";`;

const namespaceConfig = `{
  "registries": {
    "${REGISTRY_NAMESPACE}": "${REGISTRY_TEMPLATE}"
  }
}`;

const namespaceAdd = `npx shadcn@latest add ${REGISTRY_NAMESPACE}/glass-popover`;

const linkClass =
  "font-medium text-foreground/80 underline underline-offset-2 transition-colors hover:text-foreground";

function InstallationPage() {
  return (
    <DocPage
      description="Components install through the shadcn CLI straight into your project, as source files you own."
      title="Installation"
    >
      <DocSection id="prerequisites" title="Prerequisites">
        <DocProse>
          You need Tailwind CSS v4 and React 19 in a project that has been
          initialized with the shadcn CLI, so the @/components and @/lib
          aliases resolve. No runtime dependency is added; components that use
          a headless primitive pull in @base-ui/react.
        </DocProse>
      </DocSection>

      <DocSection id="core" title="Install the engine">
        <DocProse>
          Everything builds on the glass package: the lens engine, the motion
          core, and the GlassSurface overlay primitive. Installing any
          component pulls it in automatically through its registry dependency,
          so this step is optional.
        </DocProse>
        <div className="mt-4">
          <InstallTabs name="glass" />
        </div>
      </DocSection>

      <DocSection id="components" title="Install components">
        <DocProse>
          Each component ships as one file under components/ui. Swap the name
          at the end of the URL for any component in the sidebar, for example
          the popover:
        </DocProse>
        <div className="mt-4">
          <InstallTabs name="glass-popover" />
        </div>
      </DocSection>

      <DocSection id="namespace" title="Add by name">
        <DocProse>
          To install by short name instead of a full URL, register the
          {" "}
          {REGISTRY_NAMESPACE} namespace once in your components.json:
        </DocProse>
        <div className="mt-4">
          <CodeBlock code={namespaceConfig} />
        </div>
        <DocProse>Then add any component by name:</DocProse>
        <div className="mt-4">
          <CodeBlock code={namespaceAdd} lang="bash" />
        </div>
      </DocSection>

      <DocSection id="import" title="Import">
        <CodeBlock code={usage} />
        <DocProse>
          The files are yours after install. Change defaults, restyle, or rip
          out what you do not need.
        </DocProse>
      </DocSection>

      <DocSection id="ai" title="For AI agents">
        <DocProse>
          The docs are published as plain text so a coding agent can read and
          implement the components without scraping this site. Point your tool
          at{" "}
          <a className={linkClass} href="/llms.txt">
            /llms.txt
          </a>{" "}
          for an index, or{" "}
          <a className={linkClass} href="/llms-full.txt">
            /llms-full.txt
          </a>{" "}
          for every component doc plus full source in one file. Each component
          page has a markdown mirror at{" "}
          <code>/docs/components/&#123;name&#125;.md</code>, and every registry
          item carries its own usage notes, so an agent that runs the install
          command above gets the contract inline.
        </DocProse>
      </DocSection>
    </DocPage>
  );
}

export { InstallationPage };
