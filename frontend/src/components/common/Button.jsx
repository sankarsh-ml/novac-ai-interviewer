function Button({ className = "", type = "button", ...props }) {
  return <button className={className} type={type} {...props} />;
}

export default Button;
