import { REGISTRY, WIDGET_TYPES, type WidgetType } from "../canvas/registry";
import { Menu, menuItem } from "./Menu";

/** "+ Widget": lists every widget type; choosing one adds it below the board. */
export function AddWidget({ onAdd }: { onAdd: (type: WidgetType) => void }) {
  return (
    <Menu label="+ Widget" ariaLabel="Add widget" guide="add-widget">
      {(close) =>
        WIDGET_TYPES.map((type) => (
          <button
            key={type}
            type="button"
            role="menuitem"
            className={menuItem}
            onClick={() => {
              close();
              onAdd(type);
            }}
          >
            {REGISTRY[type].title}
          </button>
        ))
      }
    </Menu>
  );
}
