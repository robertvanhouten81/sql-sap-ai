from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5001)

"""

    give me per employee how many orders he or she finished and the total amount of time (actual work) @bar

    give me top 10 of the total actual costs with functional location and plant section @pie
    
    give me a percentage of the different order types @pie
    
    """
