import { createBrowserRouter } from "react-router";
import { Layout } from "./components/Layout";
import { Home } from "./pages/Home";
import { About } from "./pages/About";
import { Business } from "./pages/Business";
import { Partners } from "./pages/Partners";
import { Careers } from "./pages/Careers";
import { Contact } from "./pages/Contact";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Layout,
    children: [
      { index: true, Component: Home },
      { path: "about", Component: About },
      { path: "business", Component: Business },
      { path: "partners", Component: Partners },
      { path: "careers", Component: Careers },
      { path: "contact", Component: Contact },
    ],
  },
]);