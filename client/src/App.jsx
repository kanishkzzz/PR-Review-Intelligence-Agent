import ReviewForm from "./components/ReviewForm";

export default function App() {
  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 px-4 py-12">
      <ReviewForm onSubmit={(prUrl, token) => console.log("submitted:", prUrl, token)} loading={false} />
    </div>

    

  );
}
