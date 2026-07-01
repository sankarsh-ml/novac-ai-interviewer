function Card({ children, className = "" }) {
  return <article className={className}>{children}</article>;
}

export default Card;
