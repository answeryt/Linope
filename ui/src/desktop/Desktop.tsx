import { Dialog } from "@/desktop/dialog/Dialog";
import { useWallpaperSrc } from "@/desktop/setting/settings";
import { IslandTaskBridge } from "@/desktop/activity/IslandTaskBridge";
import { Island, IslandProvider } from "@/lib/island";

function Desktop() {
  const wallpaper = useWallpaperSrc();
  return (
    <IslandProvider>
      <IslandTaskBridge />
      <div className="fixed inset-0 overflow-hidden bg-black">
        <Dialog>
          <img
            alt=""
            className="block h-full w-full object-cover"
            draggable={false}
            src={wallpaper}
          />
        </Dialog>
      </div>
      <Island label="灵动岛" placement="viewport" />
    </IslandProvider>
  );
}

export { Desktop };
