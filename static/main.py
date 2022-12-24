import csv

with open('./emails.csv', 'r') as file:
    r = csv.reader(file)
    headers = next(r)[:-1]
    count = [0 for _ in range(len(headers))]
    tuples = []
    for row in r:
        for i in range(1, len(headers)):
            count = int(row[i])
            for _ in range(count):
                tuples.append([headers[i], row[len(headers)]])

    with open('./words.csv', 'w', newline='') as o:
        w = csv.writer(o)
        w.writerow(["word", "type"])
        for t in tuples:
            w.writerow(t)
