import { render } from "@solidjs/web";
import { initBundle } from "./state";
import { App } from "./ui/App";
import "./index.css";

render(() => <App />, document.getElementById("root")!);
initBundle();
