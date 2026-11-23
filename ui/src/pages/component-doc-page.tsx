import { useState } from "react";
import { Link } from "@/app/router";
import { ComponentPreview } from "@/components/docs/component-preview";
import { DocPage, DocProse, DocSection } from "@/components/docs/doc-page";
import { InstallSection } from "@/components/docs/install-section";
import { PropsTable } from "@/components/docs/props-table";
import { TintControl } from "@/components/docs/tint-control";
import { docBySlug } from "@/docs/registry-docs";

function ComponentDocPage({ slug }: { slug: string }) {
  const doc = docBySlug.get(slug);
  const [tint, setTint] = useState(0.5);
  const [tab, setTab] = useState<"preview" | "code">("preview");

  if (!doc) {
    return (
      <DocPage
        description="This component does not exist."
        title="Not found"
      >
        <Link className="mt-6 inline-block text-[14px] underline" to="/">
          Back to the introduction
        </Link>
      </DocPage>
    );
  }

  const Demo = doc.demo;

  return (
    <DocPage description={doc.description} title={doc.title}>
      <div className="mt-8">
        <ComponentPreview
          code={doc.demoSource}
          minHeight={doc.demoMinHeight}
          onTabChange={setTab}
        >
          <Demo tint={tint} />
        </ComponentPreview>
      </div>

      <DocSection id="installation" title="Installation">
        <InstallSection name={doc.registryName} />
      </DocSection>

      {tab === "preview" ? (
        <DocSection id="appearance" title="Appearance">
          {doc.tintable === false ? (
            <DocProse>{doc.tintNote}</DocProse>
          ) : (
            <>
              <DocProse>
                This component takes a tint prop from 0 (ultra clear) to 1
                (fully tinted), modeled on the Liquid Glass slider Apple added
                in iOS 27. The glass material tints; text and icons on it stay
                crisp. The slider below sets the tint for the demos on this
                page.
              </DocProse>
              <div className="mt-4">
                <TintControl onChange={setTint} value={tint} />
              </div>
            </>
          )}
        </DocSection>
      ) : null}

      <DocSection id="props" title="Props">
        <div className="flex flex-col gap-6">
          {doc.props.map((section) => (
            <div key={section.title}>
              {doc.props.length > 1 ? (
                <div className="mb-2 font-mono text-[13px] text-foreground">
                  {section.title}
                </div>
              ) : null}
              <PropsTable rows={section.rows} />
            </div>
          ))}
        </div>
      </DocSection>

      {doc.examples?.length ? (
        <DocSection id="examples" title="Examples">
          <div className="flex flex-col gap-10">
            {doc.examples.map((example) => {
              const Example = example.component;
              return (
                <div key={example.title}>
                  <h3 className="font-medium text-[15.5px] text-foreground">
                    {example.title}
                  </h3>
                  <p className="mt-1 mb-4 max-w-2xl text-[13.5px] text-muted-foreground leading-relaxed">
                    {example.description}
                  </p>
                  <ComponentPreview
                    code={example.source}
                    minHeight={example.minHeight}
                  >
                    <Example tint={tint} />
                  </ComponentPreview>
                </div>
              );
            })}
          </div>
        </DocSection>
      ) : null}
    </DocPage>
  );
}

export { ComponentDocPage };
