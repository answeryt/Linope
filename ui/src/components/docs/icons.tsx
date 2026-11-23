import {
  BarChart3,
  Bell as BellIcon,
  Check as CheckIcon,
  Copy as CopyIcon,
  Ellipsis as EllipsisIcon,
  House as HouseIcon,
  Info as InfoIcon,
  LayoutGrid,
  Menu as MenuIcon,
  Moon as MoonIcon,
  Pause as PauseIcon,
  Pencil as PencilIcon,
  Play as PlayIcon,
  RotateCcw,
  RotateCw,
  Search as SearchIcon,
  Settings,
  Share as ShareIcon,
  SlidersHorizontal,
  Sun as SunIcon,
  Trash2,
  X,
  type LucideIcon,
  type LucideProps,
} from "lucide-react";

function styled(Icon: LucideIcon, defaults?: LucideProps) {
  return function StyledIcon(props: LucideProps) {
    return <Icon strokeWidth={1.6} {...defaults} {...props} />;
  };
}

const Back15 = styled(RotateCcw);
const Bell = styled(BellIcon);
const Chart = styled(BarChart3);
const Check = styled(CheckIcon);
const Close = styled(X);
const Copy = styled(CopyIcon);
const Ellipsis = styled(EllipsisIcon);
const Fwd15 = styled(RotateCw);
const Gear = styled(Settings);
const Grid = styled(LayoutGrid);
const House = styled(HouseIcon);
const Info = styled(InfoIcon);
const Menu = styled(MenuIcon);
const Moon = styled(MoonIcon);
const Pause = styled(PauseIcon, { fill: "currentColor" });
const Pencil = styled(PencilIcon);
const Play = styled(PlayIcon, { fill: "currentColor" });
const Search = styled(SearchIcon);
const Share = styled(ShareIcon);
const Sliders = styled(SlidersHorizontal);
const Sun = styled(SunIcon);
const Trash = styled(Trash2);

function Github({ size = 24, absoluteStrokeWidth, strokeWidth, ...props }: LucideProps) {
  return (
    <svg
      aria-hidden="true"
      fill="currentColor"
      height={size}
      viewBox="0 0 24 24"
      width={size}
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      <path d="M12 .5C5.37.5 0 5.87 0 12.5c0 5.3 3.44 9.8 8.21 11.39.6.11.82-.26.82-.58 0-.29-.01-1.04-.02-2.05-3.34.72-4.04-1.61-4.04-1.61-.55-1.39-1.33-1.76-1.33-1.76-1.09-.74.08-.73.08-.73 1.2.09 1.84 1.24 1.84 1.24 1.07 1.83 2.81 1.3 3.5.99.11-.78.42-1.3.76-1.6-2.67-.3-5.47-1.33-5.47-5.93 0-1.31.47-2.38 1.24-3.22-.13-.3-.54-1.52.11-3.18 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 0 1 3-.4c1.02 0 2.05.14 3 .4 2.29-1.55 3.3-1.23 3.3-1.23.65 1.66.24 2.88.12 3.18.77.84 1.23 1.91 1.23 3.22 0 4.61-2.81 5.62-5.49 5.92.43.37.81 1.1.81 2.22 0 1.61-.01 2.9-.01 3.29 0 .32.21.7.82.58A12.01 12.01 0 0 0 24 12.5C24 5.87 18.63.5 12 .5Z" />
    </svg>
  );
}

export {
  Back15,
  Bell,
  Chart,
  Check,
  Close,
  Copy,
  Ellipsis,
  Fwd15,
  Gear,
  Github,
  Grid,
  House,
  Info,
  Menu,
  Moon,
  Pause,
  Pencil,
  Play,
  Search,
  Share,
  Sliders,
  Sun,
  Trash,
};
