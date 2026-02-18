const PERSIST_ATTR = "data-astro-transition-persist";
function deselectScripts(doc) {
  for (const s1 of document.scripts) {
    for (const s2 of doc.scripts) {
      if (
        // Check if the script should be rerun regardless of it being the same
        !s2.hasAttribute("data-astro-rerun") && // Inline
        (!s1.src && s1.textContent === s2.textContent || // External
        s1.src && s1.type === s2.type && s1.src === s2.src)
      ) {
        s2.dataset.astroExec = "";
        break;
      }
    }
  }
}
function swapRootAttributes(doc) {
  const html = document.documentElement;
  const astroAttributes = [...html.attributes].filter(
    ({ name }) => (html.removeAttribute(name), name.startsWith("data-astro-"))
  );
  [...doc.documentElement.attributes, ...astroAttributes].forEach(
    ({ name, value }) => html.setAttribute(name, value)
  );
}
function swapHeadElements(doc) {
  for (const el of Array.from(document.head.children)) {
    const newEl = persistedHeadElement(el, doc);
    if (newEl) {
      newEl.remove();
    } else {
      el.remove();
    }
  }
  document.head.append(...doc.head.children);
}
function swapBodyElement(newElement, oldElement) {
  oldElement.replaceWith(newElement);
  for (const el of oldElement.querySelectorAll(`[${PERSIST_ATTR}]`)) {
    const id = el.getAttribute(PERSIST_ATTR);
    const newEl = newElement.querySelector(`[${PERSIST_ATTR}="${id}"]`);
    if (newEl) {
      newEl.replaceWith(el);
      if (newEl.localName === "astro-island" && shouldCopyProps(el) && !isSameProps(el, newEl)) {
        el.setAttribute("ssr", "");
        el.setAttribute("props", newEl.getAttribute("props"));
      }
    }
  }
}
const saveFocus = () => {
  const activeElement = document.activeElement;
  if (activeElement?.closest(`[${PERSIST_ATTR}]`)) {
    if (activeElement instanceof HTMLInputElement || activeElement instanceof HTMLTextAreaElement) {
      const start = activeElement.selectionStart;
      const end = activeElement.selectionEnd;
      return () => restoreFocus({ activeElement, start, end });
    }
    return () => restoreFocus({ activeElement });
  } else {
    return () => restoreFocus({ activeElement: null });
  }
};
const restoreFocus = ({ activeElement, start, end }) => {
  if (activeElement) {
    activeElement.focus();
    if (activeElement instanceof HTMLInputElement || activeElement instanceof HTMLTextAreaElement) {
      if (typeof start === "number") activeElement.selectionStart = start;
      if (typeof end === "number") activeElement.selectionEnd = end;
    }
  }
};
const persistedHeadElement = (el, newDoc) => {
  const id = el.getAttribute(PERSIST_ATTR);
  const newEl = id && newDoc.head.querySelector(`[${PERSIST_ATTR}="${id}"]`);
  if (newEl) {
    return newEl;
  }
  if (el.matches("link[rel=stylesheet]")) {
    const href = el.getAttribute("href");
    return newDoc.head.querySelector(`link[rel=stylesheet][href="${href}"]`);
  }
  return null;
};
const shouldCopyProps = (el) => {
  const persistProps = el.dataset.astroTransitionPersistProps;
  return persistProps == null || persistProps === "false";
};
const isSameProps = (oldEl, newEl) => {
  return oldEl.getAttribute("props") === newEl.getAttribute("props");
};
const swapFunctions = {
  deselectScripts,
  swapRootAttributes,
  swapHeadElements,
  swapBodyElement,
  saveFocus
};
const swap = (doc) => {
  deselectScripts(doc);
  swapRootAttributes(doc);
  swapHeadElements(doc);
  const restoreFocusFunction = saveFocus();
  swapBodyElement(doc.body, document.body);
  restoreFocusFunction();
};
export {
  deselectScripts,
  restoreFocus,
  saveFocus,
  swap,
  swapBodyElement,
  swapFunctions,
  swapHeadElements,
  swapRootAttributes
};
