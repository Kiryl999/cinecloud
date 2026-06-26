function Features() {
  const items = [
    { title: "1. Onboarding", text: "We set up your cinema website including the booking system." },
    { title: "2. Movies & Showtimes", text: "Manage your own program through a simple admin panel." },
    { title: "3. Customers Book Directly", text: "Ticket sales, seat selection, and payment, all automated." },
  ];

  return (
    <section className="features">
      <h2>How it works</h2>
      <div className="feature-grid">
        {items.map((item) => (
          <div className="feature" key={item.title}>
            <h3>{item.title}</h3>
            <p>{item.text}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

export default Features;