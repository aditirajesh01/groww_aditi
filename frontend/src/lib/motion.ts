import type { Transition, Variants } from "motion/react";

/**
 * One place where every duration and curve lives. Every animation in this app
 * has a job: entry establishes rank order, layout closes the gap a dismissed
 * card leaves behind, expansion shows evidence growing out of the claim it
 * supports. Nothing here is decoration.
 */

export const EASE_OUT: [number, number, number, number] = [0.16, 1, 0.3, 1];
export const EASE_IN_OUT: [number, number, number, number] = [0.65, 0, 0.35, 1];

export const spring: Transition = { type: "spring", stiffness: 420, damping: 38, mass: 0.9 };
export const softSpring: Transition = { type: "spring", stiffness: 260, damping: 32 };

/** Ranked list: children enter in rank order so the eye learns the ordering. */
export const listVariants = (reduced: boolean): Variants => ({
  hidden: {},
  shown: {
    transition: reduced
      ? { duration: 0 }
      : { staggerChildren: 0.055, delayChildren: 0.04 },
  },
});

export type ExitMode = "read" | "dismissed";

/**
 * Card entry and exit.
 *
 * The two exits are deliberately different, because they mean different things.
 * "Read" settles upward and dissolves — it was consumed. "Dismissed" is thrown
 * out of the list to the left, the same direction the swipe travels, so the
 * card is visibly *leaving the attention budget* rather than merely vanishing.
 */
export const cardVariants = (reduced: boolean): Variants =>
  reduced
    ? {
        hidden: { opacity: 1 },
        shown: { opacity: 1 },
        gone: { opacity: 0, transition: { duration: 0.001 } },
      }
    : {
        hidden: { opacity: 0, y: 16, filter: "blur(3px)" },
        shown: {
          opacity: 1,
          y: 0,
          filter: "blur(0px)",
          transition: { duration: 0.5, ease: EASE_OUT },
        },
        gone: (mode: ExitMode = "read") =>
          mode === "dismissed"
            ? {
                opacity: 0,
                x: "-46%",
                scale: 0.94,
                transition: { duration: 0.3, ease: EASE_IN_OUT },
              }
            : {
                opacity: 0,
                y: -10,
                scale: 0.975,
                filter: "blur(4px)",
                transition: { duration: 0.28, ease: EASE_IN_OUT },
              },
      };

/** Evidence: a height animation, never a jump cut. */
export const heightCollapse = (reduced: boolean) =>
  reduced
    ? { initial: false as const, animate: { height: "auto", opacity: 1 }, exit: { height: 0, opacity: 0 }, transition: { duration: 0 } }
    : {
        initial: { height: 0, opacity: 0 },
        animate: { height: "auto", opacity: 1 },
        exit: { height: 0, opacity: 0 },
        transition: { height: { duration: 0.34, ease: EASE_OUT }, opacity: { duration: 0.22 } },
      };
