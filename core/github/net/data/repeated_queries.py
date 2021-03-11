IssueQuery: str = """
{
  author{
    login
    url
    avatarUrl
  }
  url
  createdAt
  closed
  closedAt
  bodyText
  title 
  number
  state
  comments {
    totalCount
  }
  participants {
    totalCount
  }
  assignees {
    totalCount
  }
  labels(first: 100) {
    nodes {
      name
    }
  }
}
"""

PullRequestQuery: str = """
{
  title
  url
  isCrossRepository
  state
  createdAt
  closed
  closedAt
  bodyText
  changedFiles
  commits(first: 250) {
    totalCount
  }
  additions
  deletions
  author {
    login 
    url
    avatarUrl
  }
  comments {
    totalCount
  }
  assignees(first: 100) {
    totalCount
    edges {
      node {
        login
        url
      }
    }
  }
  reviews(first: 100) {
    totalCount
  }
  participants(first: 100){
    totalCount
    edges {
      node {
        login
        url
      }
    }
  }
  reviewRequests(first: 100) {
    totalCount
    edges {
      node {
        requestedReviewer {
          ... on User {
            login
            url
          }
          ... on Team {
            name
            url
          }
          ... on Mannequin {
            login
            url
          }
        }
      }
    }
  }
  labels(first: 100) {
    edges {
      node {
        name
      }
    }
  }
}
"""